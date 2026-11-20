"""
GATE Intelligence Comprehensive 7-Phase Integration & Unit Test Suite.
Validates all seven pillars end-to-end:
- Phase 1: Topic-wise Question Bank
- Phase 2: Dashboard
- Phase 3: Paper Library
- Phase 4: PYQ Analytics
- Phase 5: CBT Mock Tests & Authoritative Scoring
- Phase 6: Lightweight Deterministic Agents
- Phase 7: Settings & Data Management
"""
import os
import shutil
import sqlite3
import sys
from pathlib import Path

# Add backend and tests directories to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Setup test database in writable scratch directory
REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = REPO_ROOT / "storage" / "gate_intelligence.db"
SCRATCH_DIR = Path(r"C:\Users\athar\.gemini\antigravity-cli\brain\305dbfd9-af4b-4b0e-9894-5e575eeb200b\scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = SCRATCH_DIR / "test_suite_run.db"

shutil.copy2(ORIGINAL_DB, TEST_DB)
os.environ["SQLITE_DB_PATH"] = str(TEST_DB)

from tests.direct_client import DirectTestClient
client = DirectTestClient()


def test_phase1_question_bank():
    print("\n[PHASE 1] Testing Question Bank...")

    # 1. Total questions
    res = client.get("/api/v1/questions?paper_code=CS")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    data = res.json()
    assert data["total"] == 130, f"Expected 130 total questions, got {data['total']}"
    print(f"  ✓ Total Questions: {data['total']}")

    # 2. Subject filter
    res = client.get("/api/v1/questions?paper_code=CS&subject_name=Computer+Networks")
    assert res.status_code == 200
    cn_count = res.json()["total"]
    assert cn_count > 0, "Computer Networks questions must exist"
    for item in res.json()["items"]:
        assert item["subject_name"] == "Computer Networks"
    print(f"  ✓ Subject filter (Computer Networks): {cn_count} questions")

    # 3. Year filter
    res_2012 = client.get("/api/v1/questions?paper_code=CS&examination_year=2012")
    assert res_2012.status_code == 200
    assert res_2012.json()["total"] == 65
    print(f"  ✓ Year filter (2012): {res_2012.json()['total']} questions")

    res_2013 = client.get("/api/v1/questions?paper_code=CS&examination_year=2013")
    assert res_2013.status_code == 200
    assert res_2013.json()["total"] == 65
    print(f"  ✓ Year filter (2013): {res_2013.json()['total']} questions")

    # 4. Question type filter
    res_mcq = client.get("/api/v1/questions?paper_code=CS&question_type=MCQ")
    assert res_mcq.status_code == 200
    assert res_mcq.json()["total"] > 0
    print(f"  ✓ Type filter (MCQ): {res_mcq.json()['total']} questions")

    # 5. Marks filter
    res_1m = client.get("/api/v1/questions?paper_code=CS&marks=1.0")
    assert res_1m.status_code == 200
    assert res_1m.json()["total"] > 0
    print(f"  ✓ Marks filter (1.0): {res_1m.json()['total']} questions")

    # 6. Text search query
    res_search = client.get("/api/v1/questions?paper_code=CS&search=binary+search")
    assert res_search.status_code == 200
    assert res_search.json()["total"] > 0
    print(f"  ✓ Text search ('binary search'): {res_search.json()['total']} matches")

    # 7. Practice checking: Verified 2012 question
    q2012 = res_2012.json()["items"][0]
    ans_chk = client.post(f"/api/v1/questions/{q2012['id']}/check", json={"selected_options": ["B"]})
    assert ans_chk.status_code == 200
    chk_data = ans_chk.json()
    assert chk_data["status"] == "evaluated"
    assert chk_data["is_correct"] in (True, False)
    assert chk_data["provenance"] == "official_iit"
    print(f"  ✓ Verified answer check: is_correct={chk_data['is_correct']}, provenance={chk_data['provenance']}")

    # 8. Practice checking: Unverified 2013 question
    q2013 = res_2013.json()["items"][0]
    ans_chk2 = client.post(f"/api/v1/questions/{q2013['id']}/check", json={"selected_options": ["A"]})
    assert ans_chk2.status_code == 200
    chk_data2 = ans_chk2.json()
    assert chk_data2["status"] == "unverified"
    assert chk_data2["is_correct"] is None
    print(f"  ✓ Unverified key safe handling: is_correct=None (not falsely marked)")

    # 9. Visual assets check
    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()
    cur.execute("SELECT id, relative_path FROM question_visual_assets LIMIT 1")
    asset_row = cur.fetchone()
    conn.close()
    if asset_row:
        asset_id = asset_row[0]
        res_asset = client.get(f"/api/v1/assets/{asset_id}/image")
        assert res_asset.status_code == 200
        assert res_asset.headers["content-type"] == "image/png"
        print(f"  ✓ Visual asset retrieval: asset_id='{asset_id}', length={len(res_asset.content)} bytes")


def test_phase2_dashboard():
    print("\n[PHASE 2] Testing Dashboard...")
    m1 = client.get("/api/v1/dashboard/metrics?paper_code=CS").json()
    init_attempted = m1["total_attempted"]
    print(f"  ✓ Initial attempts: {init_attempted}, total_questions: {m1['total_questions']}")

    # Submit a practice check on a 2012 question
    res_2012 = client.get("/api/v1/questions?paper_code=CS&examination_year=2012&page_size=1").json()
    q = res_2012["items"][0]
    client.post(f"/api/v1/questions/{q['id']}/check", json={"selected_options": ["B"]})

    # Verify updated metrics
    m2 = client.get("/api/v1/dashboard/metrics?paper_code=CS").json()
    assert m2["total_attempted"] >= init_attempted + 1, "Dashboard attempt count must increment"
    print(f"  ✓ Updated attempts after practice check: {m2['total_attempted']}")

    # Verify subject progress
    prog = client.get("/api/v1/dashboard/progress?paper_code=CS").json()
    assert len(prog["subjects"]) > 0
    print(f"  ✓ Subject progress: {len(prog['subjects'])} subjects tracked")

    # Verify recent activity
    rec = client.get("/api/v1/dashboard/recent?paper_code=CS").json()
    assert len(rec["activity"]) > 0
    print(f"  ✓ Recent activity log: {len(rec['activity'])} entries")


def test_phase3_paper_library():
    print("\n[PHASE 3] Testing Paper Library...")
    res = client.get("/api/v1/papers?paper_code=CS")
    assert res.status_code == 200
    papers = res.json()["papers"]
    print(f"  ✓ Papers in catalog: {len(papers)}")

    # Verify 2012 paper
    p2012 = next((p for p in papers if p["examination_year"] == 2012), None)
    assert p2012 is not None
    assert p2012["question_count"] == 65
    assert p2012["verified_keys_count"] == 65
    print(f"  ✓ Paper 2012: 65 questions, 65 verified official keys")

    # Verify 2013 paper
    p2013 = next((p for p in papers if p["examination_year"] == 2013), None)
    assert p2013 is not None
    assert p2013["question_count"] == 65
    assert p2013["verified_keys_count"] == 0
    print(f"  ✓ Paper 2013: 65 questions, 0 verified keys (Honest reporting)")

    # Verify question preview
    preview = client.get(f"/api/v1/papers/{p2012['id']}/questions").json()
    assert preview["total_questions"] == 65
    assert len(preview["questions"]) == 65
    print(f"  ✓ Paper preview: 65 sequential questions previewed")

    # Verify empty paper catalog
    res_empty = client.get("/api/v1/papers?paper_code=ME")
    assert res_empty.status_code == 200
    assert len(res_empty.json()["papers"]) == 0
    print(f"  ✓ Empty discipline (ME) handles gracefully: 0 papers")


def test_phase4_pyq_analytics():
    print("\n[PHASE 4] Testing PYQ Analytics...")
    res = client.get("/api/v1/analytics/distributions?paper_code=CS").json()

    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(subject_name, 'General'), COUNT(*)
        FROM questions
        WHERE paper_code = 'CS'
        GROUP BY subject_name
    """)
    sql_subjects = dict(cur.fetchall())
    conn.close()

    api_subjects = {s["subject_name"]: s["count"] for s in res["subject_distribution"]}
    for s_name, count in sql_subjects.items():
        assert api_subjects.get(s_name) == count, f"Mismatch for {s_name}: SQL={count}, API={api_subjects.get(s_name)}"

    print(f"  ✓ All {len(api_subjects)} subjects match direct SQL totals exactly")
    print(f"  ✓ Top topics: {len(res['topic_distribution'])}")
    print(f"  ✓ Year trends: {len(res['year_trends'])}")
    print(f"  ✓ Question types: {res['question_types']}")
    print(f"  ✓ Marks distribution: {res['marks_distribution']}")


def test_phase5_cbt_mock_tests():
    print("\n[PHASE 5] Testing CBT Mock Tests & Authoritative Scoring...")

    # 1. Start full test (GATE CS 2012: 65 questions, 100 marks)
    start_res = client.post("/api/v1/tests/start", json={
        "paper_code": "CS",
        "test_mode": "full",
        "duration_minutes": 180,
    })
    assert start_res.status_code == 200
    t_data = start_res.json()
    test_id = t_data["test_id"]
    questions = t_data["questions"]
    assert len(questions) == 65, f"Expected 65 questions, got {len(questions)}"
    assert t_data["total_marks"] == 100.0
    print(f"  ✓ Test generated: '{t_data['title']}', 65 questions, 100 marks, 180 minutes")

    # Find 1-mark and 2-mark questions
    q1 = next(q for q in questions if q["question_number"] == 1)
    q26 = next(q for q in questions if q["question_number"] == 26)
    assert q1["marks"] == 1.0
    assert q26["marks"] == 2.0

    # Official rules test:
    # Q1 (1-mark MCQ): official answer is B, submit B -> +1.0
    # Q26 (2-mark MCQ): official answer is C, submit A -> -2/3 = -0.6667
    # 63 unattempted -> 0.0
    responses = [
        {"question_id": q1["question_id"], "selected_options": ["B"], "time_spent_seconds": 30},
        {"question_id": q26["question_id"], "selected_options": ["A"], "time_spent_seconds": 60},
    ]

    sub_res = client.post(f"/api/v1/tests/{test_id}/submit", json={"responses": responses})
    assert sub_res.status_code == 200
    result = sub_res.json()

    print(f"  ✓ Authoritative scoring: obtained={result['marks_obtained']}, correct={result['correct_count']}, incorrect={result['incorrect_count']}, unattempted={result['unattempted_count']}")
    assert result["correct_count"] == 1
    assert result["incorrect_count"] == 1
    assert result["unattempted_count"] == 63
    assert abs(result["marks_obtained"] - 0.33) < 0.05, f"Expected ~0.33, got {result['marks_obtained']}"

    # Verify question review breakdown
    reviews = result["question_reviews"]
    rev_q1 = next(r for r in reviews if r["question_id"] == q1["question_id"])
    assert rev_q1["is_correct"] is True
    assert rev_q1["marks_awarded"] == 1.0

    rev_q26 = next(r for r in reviews if r["question_id"] == q26["question_id"])
    assert rev_q26["is_correct"] is False
    assert abs(rev_q26["marks_awarded"] - (-0.6667)) < 0.01

    # Verify history persistence
    hist = client.get("/api/v1/tests/history?paper_code=CS").json().get("history", [])
    assert len(hist) > 0
    assert any(h["mock_test_id"] == test_id for h in hist)
    print(f"  ✓ Test history preserved: {len(hist)} completed tests recorded")


def test_phase6_lightweight_agents():
    print("\n[PHASE 6] Testing Lightweight Deterministic Agents...")

    # Agent 1: PYQ Analysis Agent
    a1 = client.post("/api/v1/agents/pyq-analysis", json={"paper_code": "CS"}).json()
    assert a1["agent_name"] == "PYQ Analysis Agent"
    assert a1["total_questions_analyzed"] == 130
    assert len(a1["top_recurring_topics"]) > 0
    print(f"  ✓ Agent 1 (PYQ Analysis): Analyzed {a1['total_questions_analyzed']} questions, {len(a1['top_recurring_topics'])} topics")

    # Agent 2: Performance Agent
    a2 = client.post("/api/v1/agents/performance", json={"paper_code": "CS"}).json()
    assert a2["agent_name"] == "Performance Agent"
    assert a2["total_attempts"] > 0
    assert len(a2["recommendations"]) > 0
    print(f"  ✓ Agent 2 (Performance): Evaluated {a2['total_attempts']} attempts, generated {len(a2['recommendations'])} recommendations")

    # Agent 3: Question Assistant
    conn = sqlite3.connect(TEST_DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM questions WHERE examination_year = 2012 LIMIT 1")
    q_id = cur.fetchone()[0]
    conn.close()

    a3 = client.post("/api/v1/agents/question-assistant", json={"question_id": q_id}).json()
    assert a3["agent_name"] == "Question Assistant Agent"
    assert len(a3["hints"]) > 0
    print(f"  ✓ Agent 3 (Question Assistant): Generated {len(a3['hints'])} concept hints & step-by-step guidance")

    # Agent 4: Paper Analysis Agent
    a4 = client.post("/api/v1/agents/paper-analysis", json={"year": 2012, "paper_code": "CS"}).json()
    assert a4["agent_name"] == "Paper Analysis Agent"
    assert a4["total_questions"] == 65
    assert a4["answer_key_coverage_percent"] == 100.0
    print(f"  ✓ Agent 4 (Paper Analysis): {a4['total_questions']} questions, coverage {a4['answer_key_coverage_percent']}%")


def test_phase7_settings_and_data_management():
    print("\n[PHASE 7] Testing Settings & Data Management...")

    # 1. Preferences save and load
    save_res = client.post("/api/v1/settings/preferences", json={
        "theme": "light",
        "default_paper": "CS",
        "timer_alert_minutes": 10,
        "auto_save_interval_seconds": 20,
    })
    assert save_res.status_code == 200
    prefs = client.get("/api/v1/settings/preferences").json()
    assert prefs["theme"] == "light"
    assert prefs["timer_alert_minutes"] == 10
    print(f"  ✓ Preferences persisted: theme={prefs['theme']}, timer_alert={prefs['timer_alert_minutes']}m")

    # Restore dark theme
    client.post("/api/v1/settings/preferences", json={"theme": "dark", "default_paper": "CS"})

    # 2. Database backup creation
    bk_res = client.post("/api/v1/settings/backup")
    assert bk_res.status_code == 200
    bk_data = bk_res.json()
    assert Path(bk_data["backup_path"]).exists()
    print(f"  ✓ Database backup created: {bk_data['backup_filename']} ({bk_data['size_mb']} MB)")

    # 3. Import JSON validation: empty array rejection
    inv_res = client.post("/api/v1/settings/import-json", json={
        "paper_code": "CS",
        "examination_year": 2099,
        "questions": [],
    })
    assert inv_res.status_code == 400
    print(f"  ✓ Empty dataset rejected with 400 Bad Request")

    # 4. Import JSON validation: malformed record detection
    bad_rec_res = client.post("/api/v1/settings/import-json", json={
        "paper_code": "CS",
        "examination_year": 2099,
        "questions": [{"question_number": 1}],
    })
    assert bad_rec_res.status_code == 200
    assert bad_rec_res.json()["invalid"] == 1
    assert bad_rec_res.json()["imported"] == 0
    print(f"  ✓ Malformed record safely detected and skipped: invalid=1, imported=0")

    # 5. Progress reset without confirmation -> rejected
    res_no_conf = client.post("/api/v1/settings/reset-progress", json={"confirm": False})
    assert res_no_conf.status_code == 400
    print(f"  ✓ Unconfirmed progress reset rejected with 400 Bad Request")

    # 6. Valid progress reset -> resets responses, preserves question bank
    res_conf = client.post("/api/v1/settings/reset-progress", json={"confirm": True})
    assert res_conf.status_code == 200
    print(f"  ✓ Confirmed progress reset executed successfully")

    # Verify Question Bank remains intact after reset
    res_qb = client.get("/api/v1/questions?paper_code=CS").json()
    assert res_qb["total"] == 130, "Question bank must remain intact after progress reset"
    print(f"  ✓ Question Bank preserved after reset: {res_qb['total']} questions intact")


if __name__ == "__main__":
    test_phase1_question_bank()
    test_phase2_dashboard()
    test_phase3_paper_library()
    test_phase4_pyq_analytics()
    test_phase5_cbt_mock_tests()
    test_phase6_lightweight_agents()
    test_phase7_settings_and_data_management()
    print("\n" + "=" * 60)
    print(">>> ALL 7 PHASES INTEGRATION TESTS PASSED 100% SUCCESSFULLY <<<")
    print("=" * 60 + "\n")
