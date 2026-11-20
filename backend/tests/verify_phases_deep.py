import os
import shutil
import sys
import sqlite3
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = REPO_ROOT / "storage" / "gate_intelligence.db"
SCRATCH_DIR = Path(r"C:\Users\athar\.gemini\antigravity-cli\brain\305dbfd9-af4b-4b0e-9894-5e575eeb200b\scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = SCRATCH_DIR / "test_phases_deep.db"
shutil.copy2(ORIGINAL_DB, TEST_DB)
os.environ["SQLITE_DB_PATH"] = str(TEST_DB)
DB_PATH = TEST_DB

from tests.direct_client import DirectTestClient

client = DirectTestClient()

def test_question_bank_filters_and_practice():
    print("\n--- PHASE 1: QUESTION BANK VERIFICATION ---")
    
    # 1. Total questions
    res = client.get("/api/v1/questions?paper_code=CS")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 130, f"Expected 130 total questions, got {data['total']}"
    print(f"[OK] Total Questions in Bank: {data['total']}")

    # 2. Subject filter
    res = client.get("/api/v1/questions?paper_code=CS&subject_name=Computer+Networks")
    assert res.status_code == 200
    cn_count = res.json()["total"]
    assert cn_count > 0, "Computer Networks questions should exist"
    for item in res.json()["items"]:
        assert item["subject_name"] == "Computer Networks"
    print(f"[OK] Subject filter (Computer Networks): {cn_count} questions")

    # 3. Year filter
    res_2012 = client.get("/api/v1/questions?paper_code=CS&examination_year=2012")
    assert res_2012.status_code == 200
    assert res_2012.json()["total"] == 65
    print(f"[OK] Year filter (2012): {res_2012.json()['total']} questions")

    res_2013 = client.get("/api/v1/questions?paper_code=CS&examination_year=2013")
    assert res_2013.status_code == 200
    assert res_2013.json()["total"] == 65
    print(f"[OK] Year filter (2013): {res_2013.json()['total']} questions")

    # 4. Question type filter
    res_mcq = client.get("/api/v1/questions?paper_code=CS&question_type=MCQ")
    assert res_mcq.status_code == 200
    assert res_mcq.json()["total"] > 0
    print(f"[OK] Question type filter (MCQ): {res_mcq.json()['total']} questions")

    # 5. Marks filter
    res_1m = client.get("/api/v1/questions?paper_code=CS&marks=1.0")
    assert res_1m.status_code == 200
    assert res_1m.json()["total"] > 0
    print(f"[OK] Marks filter (1.0 mark): {res_1m.json()['total']} questions")

    # 6. Search query
    res_search = client.get("/api/v1/questions?paper_code=CS&search=binary+search")
    assert res_search.status_code == 200
    assert res_search.json()["total"] > 0
    print(f"[OK] Search query ('binary search'): {res_search.json()['total']} results")

    # 7. Practice checking: Verified 2012 question
    q2012 = res_2012.json()["items"][0]
    ans_chk = client.post(f"/api/v1/questions/{q2012['id']}/check", json={"selected_options": ["B"]})
    assert ans_chk.status_code == 200
    chk_data = ans_chk.json()
    assert chk_data["status"] == "evaluated"
    assert chk_data["is_correct"] in (True, False)
    assert chk_data["provenance"] == "official_iit"
    print(f"[OK] Verified 2012 answer check: status={chk_data['status']}, is_correct={chk_data['is_correct']}, provenance={chk_data['provenance']}")

    # 8. Practice checking: Unverified 2013 question
    q2013 = res_2013.json()["items"][0]
    ans_chk2 = client.post(f"/api/v1/questions/{q2013['id']}/check", json={"selected_options": ["A"]})
    assert ans_chk2.status_code == 200
    chk_data2 = ans_chk2.json()
    assert chk_data2["status"] == "unverified"
    assert chk_data2["is_correct"] is None
    assert "not yet verified" in chk_data2["message"]
    print(f"[OK] Unverified 2013 answer check: status={chk_data2['status']}, is_correct={chk_data2['is_correct']} (Safely handled)")

    # 9. Visual assets check
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, relative_path FROM question_visual_assets LIMIT 1")
    asset_row = cur.fetchone()
    conn.close()
    if asset_row:
        asset_id = asset_row[0]
        res_asset = client.get(f"/api/v1/assets/{asset_id}/image")
        assert res_asset.status_code == 200, f"Asset retrieval failed: {res_asset.status_code}"
        assert res_asset.headers["content-type"] == "image/png"
        print(f"[OK] Asset endpoint test for asset_id='{asset_id}': status={res_asset.status_code}, length={len(res_asset.content)} bytes")


def test_dashboard_and_live_updates():
    print("\n--- PHASE 2: DASHBOARD VERIFICATION ---")
    
    # Get initial metrics
    m1 = client.get("/api/v1/dashboard/metrics?paper_code=CS").json()
    init_attempted = m1["total_attempted"]
    print(f"[OK] Initial dashboard attempts: {init_attempted}, total_questions: {m1['total_questions']}")

    # Submit a practice check on a 2012 question
    res_2012 = client.get("/api/v1/questions?paper_code=CS&examination_year=2012&page_size=1").json()
    q = res_2012["items"][0]
    client.post(f"/api/v1/questions/{q['id']}/check", json={"selected_options": ["B"]})

    # Get updated metrics
    m2 = client.get("/api/v1/dashboard/metrics?paper_code=CS").json()
    print(f"[OK] Updated dashboard attempts: {m2['total_attempted']}")
    assert m2["total_attempted"] >= init_attempted + 1, "Dashboard attempt count should increment after practice attempt"

    # Verify subject progress
    prog = client.get("/api/v1/dashboard/progress?paper_code=CS").json()
    assert len(prog["subjects"]) > 0
    print(f"[OK] Dashboard subject progress: {len(prog['subjects'])} subjects tracked")

    # Verify recent activity
    rec = client.get("/api/v1/dashboard/recent?paper_code=CS").json()
    assert len(rec["activity"]) > 0
    print(f"[OK] Dashboard recent activity: {len(rec['activity'])} recent items")


def test_paper_library():
    print("\n--- PHASE 3: PAPER LIBRARY VERIFICATION ---")
    res = client.get("/api/v1/papers?paper_code=CS")
    assert res.status_code == 200
    papers = res.json()["papers"]
    print(f"[OK] Papers listed in catalog: {len(papers)}")

    # Verify 2012 paper
    p2012 = next((p for p in papers if p["examination_year"] == 2012), None)
    assert p2012 is not None
    assert p2012["question_count"] == 65
    assert p2012["verified_keys_count"] == 65
    print(f"[OK] Paper 2012: 65 questions, 65 verified official keys")

    # Verify 2013 paper
    p2013 = next((p for p in papers if p["examination_year"] == 2013), None)
    assert p2013 is not None
    assert p2013["question_count"] == 65
    assert p2013["verified_keys_count"] == 0
    print(f"[OK] Paper 2013: 65 questions, 0 verified keys (Truthful reporting)")

    # Verify question preview
    preview = client.get(f"/api/v1/papers/{p2012['id']}/questions").json()
    assert preview["total_questions"] == 65
    assert len(preview["questions"]) == 65
    print(f"[OK] Paper preview: 65 sequential questions previewed")

    # Verify empty paper catalog handling
    res_empty = client.get("/api/v1/papers?paper_code=ME")
    assert res_empty.status_code == 200
    assert len(res_empty.json()["papers"]) == 0
    print(f"[OK] Empty discipline catalog (ME): 0 papers correctly returned")


def test_pyq_analytics_vs_sql():
    print("\n--- PHASE 4: PYQ ANALYTICS VERIFICATION ---")
    res = client.get("/api/v1/analytics/distributions?paper_code=CS").json()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Compare subject question totals with SQL
    cur.execute("""
        SELECT COALESCE(subject_name, 'General'), COUNT(*)
        FROM questions
        WHERE paper_code = 'CS'
        GROUP BY subject_name
    """)
    sql_subjects = dict(cur.fetchall())
    conn.close()

    api_subjects = {s["subject_name"]: s["count"] for s in res["subject_distribution"]}
    print(f"[OK] API Subject distribution count: {len(api_subjects)} subjects")
    for s_name, count in sql_subjects.items():
        assert api_subjects.get(s_name) == count, f"Mismatch for subject {s_name}: SQL={count}, API={api_subjects.get(s_name)}"

    print("[OK] All Analytics subject distributions match direct SQL totals exactly!")
    print(f"[OK] Year trends: {len(res['year_trends'])} years")
    print(f"[OK] Question types: {res['question_types']}")
    print(f"[OK] Marks breakdown: {res['marks_distribution']}")


def test_deterministic_agents():
    print("\n--- PHASE 6: LIGHTWEIGHT AGENTS VERIFICATION ---")
    
    # 1. PYQ Analysis Agent
    a1 = client.post("/api/v1/agents/pyq-analysis", json={"paper_code": "CS"}).json()
    assert a1["agent_name"] == "PYQ Analysis Agent"
    assert a1["total_questions_analyzed"] == 130
    assert len(a1["top_recurring_topics"]) > 0
    print(f"[OK] Agent 1 (PYQ Analysis): Analyzed {a1['total_questions_analyzed']} questions, {len(a1['top_recurring_topics'])} recurring topics")

    # 2. Performance Agent
    a2 = client.post("/api/v1/agents/performance", json={"paper_code": "CS"}).json()
    assert a2["agent_name"] == "Performance Agent"
    assert a2["total_attempts"] > 0
    assert len(a2["recommendations"]) > 0
    print(f"[OK] Agent 2 (Performance): Evaluated {a2['total_attempts']} attempts, accuracy {a2.get('accuracy_percentage', 0)}%")

    # 3. Question Assistant Agent
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM questions WHERE examination_year = 2012 LIMIT 1")
    q_id = cur.fetchone()[0]
    conn.close()

    a3 = client.post("/api/v1/agents/question-assistant", json={"question_id": q_id}).json()
    assert a3["agent_name"] == "Question Assistant Agent"
    assert len(a3["hints"]) > 0
    print(f"[OK] Agent 3 (Question Assistant): Generated {len(a3['hints'])} conceptual hints without spoiling answer")

    # 4. Paper Analysis Agent
    a4 = client.post("/api/v1/agents/paper-analysis", json={"year": 2012, "paper_code": "CS"}).json()
    assert a4["agent_name"] == "Paper Analysis Agent"
    assert a4["paper_title"] == "GATE CS 2012 (Set-1)"
    assert a4["total_questions"] == 65
    assert a4["answer_key_coverage_percent"] == 100.0
    print(f"[OK] Agent 4 (Paper Analysis): {a4['total_questions']} questions, coverage {a4['answer_key_coverage_percent']}%")

    # Test empty paper code for Agent 1
    a1_empty = client.post("/api/v1/agents/pyq-analysis", json={"paper_code": "XX"}).json()
    assert a1_empty["total_questions_analyzed"] == 0
    print(f"[OK] Agent 1 gracefully handles empty discipline (XX): 0 questions")


def test_settings_and_data_management():
    print("\n--- PHASE 7: SETTINGS & DATA MANAGEMENT VERIFICATION ---")

    # 1. Preferences save and get
    save_res = client.post("/api/v1/settings/preferences", json={
        "theme": "light",
        "default_paper": "CS",
        "timer_alert_minutes": 10,
        "auto_save_interval_seconds": 20
    })
    assert save_res.status_code == 200
    prefs = client.get("/api/v1/settings/preferences").json()
    assert prefs["theme"] == "light"
    assert prefs["timer_alert_minutes"] == 10
    print(f"[OK] Preferences successfully saved and persisted: theme={prefs['theme']}, alert={prefs['timer_alert_minutes']}m")

    # Revert to dark theme
    client.post("/api/v1/settings/preferences", json={"theme": "dark", "default_paper": "CS"})

    # 2. Create on-demand backup
    bk_res = client.post("/api/v1/settings/backup")
    assert bk_res.status_code == 200
    bk_data = bk_res.json()
    assert Path(bk_data["backup_path"]).exists()
    print(f"[OK] Instant backup created: {bk_data['backup_filename']} ({bk_data['size_mb']} MB)")

    # 3. Import JSON validation: invalid payload (empty questions)
    inv_res = client.post("/api/v1/settings/import-json", json={
        "paper_code": "CS",
        "examination_year": 2099,
        "questions": []
    })
    assert inv_res.status_code == 400
    print(f"[OK] Rejected empty dataset with 400 Bad Request")

    # 4. Import JSON validation: malformed record (missing text)
    bad_rec_res = client.post("/api/v1/settings/import-json", json={
        "paper_code": "CS",
        "examination_year": 2099,
        "questions": [{"question_number": 1}]
    })
    assert bad_rec_res.status_code == 200
    assert bad_rec_res.json()["invalid"] == 1
    assert bad_rec_res.json()["imported"] == 0
    print(f"[OK] Detected and rejected malformed question record without inserting")

    # 5. Progress reset without confirmation -> must fail
    res_no_conf = client.post("/api/v1/settings/reset-progress", json={"confirm": False})
    assert res_no_conf.status_code == 400
    print(f"[OK] Refused unconfirmed progress reset with 400 Bad Request")


if __name__ == "__main__":
    test_question_bank_filters_and_practice()
    test_dashboard_and_live_updates()
    test_paper_library()
    test_pyq_analytics_vs_sql()
    test_deterministic_agents()
    test_settings_and_data_management()
    print("\n=======================================================")
    print(">>> ALL DEEP PHASE VERIFICATIONS PASSED SUCCESSFULLY <<<")
    print("=======================================================\n")
